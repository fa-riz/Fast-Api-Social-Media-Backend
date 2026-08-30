from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, oauth2
from ..database import get_db

router = APIRouter( 
    tags=['Votes']
    )

@router.post("/votes", status_code=status.HTTP_201_CREATED)
def vote(vote: schemas.Vote, db: Session = Depends(get_db), current_user: int = Depends(oauth2.get_current_user)):
    if vote.dir == 1:
        # Check if the user has already voted for the post
        existing_vote = db.query(models.Votes).filter(models.Votes.post_id == vote.post_id, models.Votes.user_id == current_user.id).first()
        if existing_vote:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already voted for this post.")
        if not db.query(models.Posts).filter(models.Posts.id == vote.post_id).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
        
        # Create a new vote
        new_vote = models.Votes(post_id=vote.post_id, user_id=current_user.id)
        db.add(new_vote)
        db.commit()
        return {"message": "Successfully added vote."}
    else:
        # Check if the user has already voted for the post
        existing_vote = db.query(models.Votes).filter(models.Votes.post_id == vote.post_id, models.Votes.user_id == current_user.id).first()
        if not existing_vote:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vote does not exist.")
        
        # Remove the existing vote
        db.delete(existing_vote)
        db.commit()
        return {"message": "Successfully removed vote."}
