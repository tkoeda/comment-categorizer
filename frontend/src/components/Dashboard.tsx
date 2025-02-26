import React from "react";
import CombineReviewsForm from "./CombineReviewsForm";
import CleanReviewsForm from "./CleanReviewsForm";
import ProcessReviewsForm from "./ProcessReviewsForm";
import ManageIndustries from "./ManageIndustries";
import DeleteFileForm from "./DeleteFileForm";

const Dashboard: React.FC = () => {
    return (
        <div>
            <h1>Review Processing Dashboard</h1>
            <div>
                <CombineReviewsForm />
                <hr />
                <CleanReviewsForm />
                <hr />
                <ProcessReviewsForm />
                <hr />
                <ManageIndustries />
                <hr />
                <DeleteFileForm />
            </div>
        </div>
    );
};

export default Dashboard;
